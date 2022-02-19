from operator import le
from django.db.models import Q
from djmoney.money import Money
from rest_framework import serializers
from asgiref.sync import async_to_sync
from accounts.models import User
from instructor.models import Coach, CoachApplication
from posts.models import Post, PostImage, PostVideo, PlaybackId
from projects.models import Project, Prerequisite, Milestone, Team, MilestoneCompletionReport, MilestoneCompletionImage, MilestoneCompletionPlaybackId, MilestoneCompletionVideo, Coupon
from comments.models import CommentImage, Comment
from subscribers.models import Subscriber, SubscriberAvatar, Subscription
from expertisefields.models import ExpertiseField, ExpertiseFieldAvatar
from tiers.models import Tier, Benefit
from reacts.models import React
from chat.models import ChatRoom, Message, MessageImage
from awards.models import Award, AwardBase
from qa.models import Question, QuestionInvitation, QaSession, CommonQuestion, AvailableTimeRange
from babel.numbers import get_currency_precision
import channels.layers
import stripe
from decimal import Decimal
import json
import os

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


def money_to_integer(money):
    try:
        return int(
            money.amount * (
                10 ** get_currency_precision(money.currency.code)
            )
        )
    except AttributeError as e:
        return int(
            int(money) * (
                10 ** get_currency_precision('eur')
            )
        )


class QaSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QaSession
        fields = ['surrogate', 'minutes', 'credit', 'product_id', 'price_id']


class CommonQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommonQuestion
        fields = '__all__'


class AvailableTimeRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailableTimeRange
        fields = ['id', 'weekday', 'start_time', 'end_time']


class CoachSerializer(serializers.ModelSerializer):
    expertise_field = serializers.StringRelatedField()
    avatar = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    tier = serializers.SerializerMethodField()
    tiers = serializers.SerializerMethodField()
    tier_full = serializers.SerializerMethodField()
    coupon = serializers.SerializerMethodField()
    number_of_projects_joined = serializers.SerializerMethodField()
    qa_sessions = serializers.SerializerMethodField()
    common_questions = serializers.SerializerMethodField()
    available_time_ranges = serializers.SerializerMethodField()

    @staticmethod
    def get_avatar(coach):
        if coach.avatar:
            return coach.avatar.image.url
        return None

    def get_projects(self, coach):
        context = {
            "request": self.context["request"]
        }
        return ProjectSerializer(coach.created_projects.all(), many=True, context=context).data

    def get_tier(self, coach):
        try:
            user = self.context['request'].user
            if user.is_authenticated:
                if user.subscriber.subscriptions.filter(tier__coach=coach).exists():
                    return user.subscriber.subscriptions.filter(tier__coach=coach).first().tier.get_tier_display()
        except KeyError:
            return None

    def get_tier_full(self, coach):
        try:
            user = self.context['request'].user
            if user.is_authenticated:
                if user.subscriber.subscriptions.filter(tier__coach=coach).exists():
                    return TierSerializer(user.subscriber.subscriptions.filter(tier__coach=coach).first().tier).data
        except KeyError:
            return None

    def get_coupon(self, coach):
        try:
            user = self.context['request'].user
            if user.is_authenticated:
                coupon = Coupon.objects.filter(subscriber=user.subscriber, coach=coach)
                if coupon.exists():
                    return CouponSerializer(coupon.first()).data
        except KeyError:
            return None

    def get_qa_sessions(self, coach):
        context = {
            "request": self.context["request"]
        }
        return QaSessionSerializer(coach.qa_sessions.all(), many=True, context=context).data

    def get_common_questions(self, coach):
        context = {
            "request": self.context["request"]
        }
        return CommonQuestionSerializer(coach.common_questions.all(), many=True, context=context).data

    def get_available_time_ranges(self, coach):
        context = {
            "request": self.context["request"]
        }
        return AvailableTimeRangeSerializer(coach.available_time_ranges.all(), many=True, context=context).data


    # get number of projects the user has subscribed to for this coach
    # this is used for frontend validation because Tier 1 subscribers only have access to one project
    # and free subs have access to none
    def get_number_of_projects_joined(self, coach):
        try:
            user = self.context['request'].user
            if user.is_authenticated:
                if user.subscriber.subscriptions.filter(tier__coach=coach).exists():
                    return Team.objects.filter(project__coach=coach, members__in=[user.subscriber]).count()
        except KeyError:
            return None

    def get_tiers(self, coach):
        return TierSerializer(coach.tiers.all(), many=True).data

    class Meta:
        model = Coach
        fields = ['name', 'avatar', 'bio', 'expertise_field', 'projects', 'number_of_projects_joined',
                  'tier', 'tier_full', 'tiers', 'qa_sessions', 'available_time_ranges', 'common_questions', 'surrogate', 
                  'charges_enabled', 'coupon', 'seen_welcome_page', 'submitted_expertise', 'qa_session_credit']


class CoachApplicationSerializer(serializers.ModelSerializer):
    subscriber = serializers.StringRelatedField()

    def create(self, validated_data):
        user = self.context['request'].user
        application = CoachApplication.objects.create(
            subscriber=user.subscriber, **validated_data)
        return application

    class Meta:
        model = CoachApplication
        fields = ['surrogate', 'subscriber', 'message']
        read_only_fields = ['surrogate', 'subscriber']


class SubscriberSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, subscriber):
        return subscriber.surrogate

    @staticmethod
    def get_avatar(sub):
        if sub.avatar:
            return sub.avatar.image.url
        return None

    class Meta:
        model = Subscriber
        fields = ['name', 'avatar', 'xp', 'level', 'level_progression', 'id']
        read_only_fields = ['id', 'xp', 'level', 'level_progression']


class SubscriberAvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriberAvatar
        fields = '__all__'


class SubscriberUpdateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False)
    id = serializers.SerializerMethodField()

    def get_id(self, subscriber):
        return subscriber.surrogate

    def update(self, instance, validated_data):
        try:
            avatar = validated_data.pop('avatar')
            new_avatar = SubscriberAvatar.objects.create(
                subscriber=instance, image=avatar)
            #instance.avatar.image = avatar
        except KeyError:
            pass

        instance = super(SubscriberUpdateSerializer, self).update(
            instance, validated_data)
        return instance

    class Meta:
        model = Subscriber
        fields = ['name', 'avatar', 'id']
        read_only_fields = ['id']


class UserSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    subscriber = SubscriberSerializer()

    class Meta:
        model = User
        fields = ['username', 'email', 'is_coach',
                  'is_subscriber', 'coach', 'subscriber']


class UserMeSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    subscriber = SubscriberSerializer()
    subscriber_data = serializers.SerializerMethodField()

    def get_subscriber_data(self, user):
        if not user.coach:
            return None
        sub_count = Subscription.objects.filter(
            tier__coach=user.coach).count()  # user.coach.subscribers.count()
        free_sub_count = Subscription.objects.filter(
            tier__tier=Tier.FREE, tier__coach=user.coach).count()
        tier1_sub_count = Subscription.objects.filter(
            tier__tier=Tier.TIER1, tier__coach=user.coach).count()
        tier2_sub_count = Subscription.objects.filter(
            tier__tier=Tier.TIER2, tier__coach=user.coach).count()
        return {'subscribers_count': sub_count, 'free_subscribers_count': free_sub_count,
                'tier1_subscribers_count': tier1_sub_count, 'tier2_subscribers_count': tier2_sub_count}

    class Meta:
        model = User
        fields = ['username', 'email', 'is_coach', 'is_subscriber',
                  'coach', 'subscriber', 'subscriber_data']


class UserMeNoCoachSerializer(serializers.ModelSerializer):
    subscriber = SubscriberSerializer()
    is_coach_application_pending = serializers.SerializerMethodField()

    def get_is_coach_application_pending(self, user):
        try:
            applications = CoachApplication.objects.filter(subscriber=user.subscriber)
            if applications.exists():
                latest_application = CoachApplication.objects.order_by('-created')[0]
                if latest_application.status == CoachApplication.PENDING:
                    return True
            return False
        except Exception as e:
            print("UserMeNoCoachSerializer error", e)
            return False

    class Meta:
        model = User
        fields = ['username', 'email', 'is_coach',
                  'is_subscriber', 'is_coach_application_pending', 'subscriber']


class PrerequisiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prerequisite
        fields = ['description']


class MilestoneCompletionImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, milestone_report):
        if milestone_report.image:
            return milestone_report.image.url
        return None

    class Meta:
        model = MilestoneCompletionImage
        fields = ['width', 'height', 'image']


class MilestoneCompletionPlaybackSerializer(serializers.ModelSerializer):
    class Meta:
        model = MilestoneCompletionPlaybackId
        fields = ['playback_id', 'policy']


class MilestoneCompletionVideoSerializer(serializers.ModelSerializer):
    playback_ids = MilestoneCompletionPlaybackSerializer(many=True)

    class Meta:
        model = MilestoneCompletionVideo
        fields = ['asset_id', 'playback_ids']


class CreateMilestoneCompletionReportSerializer(serializers.ModelSerializer):
    members = serializers.ListField(
        child=serializers.UUIDField(), write_only=True)
    images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False)

    def create(self, validated_data):
        milestone_id = self.context['milestone_id']

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []

        try:
            members = validated_data.pop('members')
        except KeyError:
            members = []

        milestone = Milestone.objects.filter(id=milestone_id).first()
        milestone_report = MilestoneCompletionReport.objects.create(
            milestone=milestone, **validated_data)

        for image in images:
            MilestoneCompletionImage.objects.create(
                milestone_completion_report=milestone_report, image=image)

        for member in members:
            _member = Subscriber.objects.filter(surrogate=member)
            # find team from members
            # this is not really optimal but whatever
            team = _member.first().teams.filter(project=milestone.project).first()
            milestone_report.team = team
            milestone_report.members.set(_member)

        milestone_report.save()
        return milestone_report

    class Meta:
        model = MilestoneCompletionReport
        fields = ['surrogate', 'members', 'team', 'message', 'milestone', 'images']
        read_only_fields = ['milestone', 'surrogate', 'team']


class CoachUpdateMilestoneCompletionReportSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True, required=False)
    images = MilestoneCompletionImageSerializer(many=True, required=False)
    videos = MilestoneCompletionVideoSerializer(many=True, required=False)

    class Meta:
        model = MilestoneCompletionReport
        fields = ['surrogate', 'members', 'team', 'message', 'coach_feedback', 'milestone', 'images', 'videos', 'status']
        read_only_fields = ['milestone', 'surrogate', 'team', 'message', 'members', 'images', 'videos']


class MilestoneCompletionReportSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True, required=False)
    images = MilestoneCompletionImageSerializer(many=True, required=False)
    videos = MilestoneCompletionVideoSerializer(many=True, required=False)

    class Meta:
        model = MilestoneCompletionReport
        fields = ['members', 'message', 'milestone', 'coach_feedback', 'status',
                  'images', 'videos', 'surrogate']
        read_only_fields = fields


class MyCouponSerializer(serializers.ModelSerializer):
    coach = serializers.SerializerMethodField()
    subscriber = SubscriberSerializer()

    def get_coach(self, coupon):
        return {
            'coach_id': coupon.coach.surrogate
        }

    class Meta:
        model = Coupon
        fields = ['surrogate', 'coupon_id', 'subscriber', 'coach', 'valid', 'json_data']
        read_only_fields = fields


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['surrogate', 'coupon_id', 'valid', 'json_data']
        read_only_fields = fields


class MilestoneSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    def get_id(self, milestone):
        return milestone.surrogate

    class Meta:
        model = Milestone
        fields = ['description', 'id']
        read_only_fields = ['id']


class ProjectSerializer(serializers.ModelSerializer):
    prerequisites = PrerequisiteSerializer(many=True)
    milestones = MilestoneSerializer(many=True)
    difficulty = serializers.SerializerMethodField()
    linked_posts_count = serializers.SerializerMethodField()
    coach_data = serializers.SerializerMethodField()
    coach = serializers.SerializerMethodField()
    team_data = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, project):
        return project.surrogate

    def get_difficulty(self, project):
        return project.get_difficulty_display()

    def get_linked_posts_count(self, project):
        return project.posts.count()

    def get_coach_data(self, project):
        number_of_projects_joined = None
        my_tier = None

        try:
            user = self.context['request'].user
            if user.is_authenticated:
                if user.subscriber.subscriptions.filter(tier__coach=project.coach).exists():
                    subscription = user.subscriber.subscriptions.filter(
                        tier__coach=project.coach).first()
                    my_tier = subscription.tier
                    number_of_projects_joined = Team.objects.filter(
                        project__coach=project.coach, members__in=[user.subscriber]).count()
        except KeyError:
            number_of_projects_joined = None

        return {'number_of_projects_joined': number_of_projects_joined, "id": project.coach.surrogate, "my_tier": TierSerializer(my_tier).data}

    def get_coach(self, project):
        avatar = None
        if project.coach.avatar:
            avatar = project.coach.avatar.image.url
        return {'name': project.coach.name, 'avatar': avatar}

    def get_team_data(self, project):
        try:
            user = self.context['request'].user
            if user.is_authenticated:
                # check if this user owns this project
                if user.is_coach and project.coach == user.coach:
                    team_count = Team.objects.filter(project=project).count()

                    # no need to return only the ACCEPTED milestones
                    number_of_tasks_completed = MilestoneCompletionReport.objects.filter(
                        milestone__project=project).filter(Q(status=MilestoneCompletionReport.PENDING) | Q(status=MilestoneCompletionReport.ACCEPTED)).distinct('milestone', 'team').count()

                    number_of_tasks_reviewed = MilestoneCompletionReport.objects.filter(
                        milestone__project=project, status=MilestoneCompletionReport.ACCEPTED).count()
                    number_of_tasks_not_reviewed = MilestoneCompletionReport.objects.filter(
                        milestone__project=project, status=MilestoneCompletionReport.PENDING).distinct('milestone', 'team').count()
                    return {'team_count': team_count, 'number_of_tasks_completed': number_of_tasks_completed, 'number_of_tasks_reviewed': number_of_tasks_reviewed, 'number_of_tasks_not_reviewed': number_of_tasks_not_reviewed}
        except KeyError:
            return None

    class Meta:
        model = Project
        fields = ['name', 'credit', 'description', 'difficulty', 'linked_posts_count', 'coach',
                  'team_size', 'prerequisites', 'milestones', 'coach_data', 'team_data', 'id']
        read_only_fields = ['linked_posts', 'coach_data', 'team_data', 'coach']


class CreateOrUpdateProjectSerializer(serializers.ModelSerializer):
    # the below 2 contain a list of descriptions for both prerequisites and milestones
    prerequisites = serializers.ListField(
        child=serializers.CharField(allow_blank=True), write_only=True, required=False)
    milestones = serializers.ListField(
        child=serializers.JSONField(), write_only=True, required=False)
    attached_posts = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False)
    credit = serializers.CharField(write_only=True, required=False)

    def create(self, validated_data):
        coach = self.context['request'].user.coach

        if not validated_data.get('name'):
            raise serializers.ValidationError({'error': 'A name is required'})

        if not validated_data.get('description'):
            raise serializers.ValidationError({'error': 'A description is required'})

        if not validated_data.get('difficulty'):
            raise serializers.ValidationError({'error': 'A difficulty is required'})

        try:
            prerequisites = validated_data.pop('prerequisites')
        except KeyError:
            prerequisites = []

        try:
            milestones = validated_data.pop('milestones')
        except KeyError:
            raise serializers.ValidationError({'error': 'At least one milestone is required'})
            #milestones = []

        if len(milestones) == 0:
            raise serializers.ValidationError({'error': 'At least one milestone is required'})

        # do this once before creating the project
        for milestone in milestones:
            try:
                if not isinstance(milestone, dict):
                    milestone = json.loads(milestone)
            # helps pass tests
            except json.decoder.JSONDecodeError:
                import ast
                milestone = ast.literal_eval(milestone)

            if not milestone.get('description'):
                raise serializers.ValidationError({'error': 'One or more milestones are missing the "description" field'})

        try:
            attached_posts = validated_data.pop('attached_posts')
        except KeyError:
            attached_posts = []

        project = Project.objects.create(coach=coach, **validated_data)

        # alternatively instead of iterating create a queryset from the 'attached_posts' and
        # add it to the linked_project using the asterisk notation
        for post_id in attached_posts:
            post = Post.objects.get(surrogate=post_id)
            post.linked_project = project
            post.save()

        for prerequisite in prerequisites:
            # make sure it's not empty string
            if prerequisite:
                Prerequisite.objects.create(
                    description=prerequisite, project=project)

        for milestone in milestones:
            try:
                if not isinstance(milestone, dict):
                    milestone = json.loads(milestone)
            # helps pass tests
            except json.decoder.JSONDecodeError:
                import ast
                milestone = ast.literal_eval(milestone)
            # validation has been done beforehand
            Milestone.objects.create(
                description=milestone['description'], project=project)

        return project

    def update(self, instance, validated_data):
        coach = self.context['request'].user.coach

        try:
            prerequisites = validated_data.pop('prerequisites')
        except KeyError:
            prerequisites = []

        # prerequisites are safe to delete and recreate
        instance.prerequisites.all().delete()
        for prerequisite in prerequisites:
            Prerequisite.objects.create(
                description=prerequisite, project=instance)

        # milestones need to be iterated and updated separately since they have
        # multiple relations attached to them
        try:
            milestones = validated_data.pop('milestones')
        except KeyError:
            milestones = []

        # default project price
        credit = instance.credit

        try:
            new_credit = validated_data.pop('credit')
            credit = Money(new_credit.replace(',', '.'), 'EUR')
        except Exception as e:
            pass

        try:
            difficulty = validated_data.pop('difficulty')
            instance.difficulty = difficulty
        except Exception as e:
            pass
        instance.credit = credit

        for milestone in milestones:
            try:
                if not isinstance(milestone, dict):
                    milestone = json.loads(milestone)
            # helps pass tests
            except json.decoder.JSONDecodeError:
                import ast
                milestone = ast.literal_eval(milestone)

            if not milestone.get('description'):
                raise serializers.ValidationError({'error': 'One or more milestones are missing the "description" field'})

            # try:
            milestone_instance = Milestone.objects.filter(
                surrogate=milestone.get('id'))
            if milestone_instance.exists():
                milestone_instance = milestone_instance.first()
                milestone_instance.description = milestone['description']
                milestone_instance.save()
            else:
                Milestone.objects.create(
                    description=milestone['description'], project=instance)
            # error might be thrown if the provided id is not a valid pk
            # except Exception as e:
                # Milestone.objects.create(description=milestone['description'], project=instance)

        try:
            attached_posts = validated_data.pop('attached_posts')
            # if user has provided new attached posts clear the old ones
            instance.posts.clear()
        except KeyError:
            attached_posts = []
        for post_id in attached_posts:
            post = Post.objects.get(surrogate=post_id)
            post.linked_project = instance
            post.save()
        instance = super(CreateOrUpdateProjectSerializer,
                         self).update(instance, validated_data)
        return instance

    class Meta:
        model = Project
        fields = ['name', 'credit', 'description', 'difficulty', 'team_size',
                  'prerequisites', 'milestones', 'attached_posts', 'id', 'surrogate']
        read_only_fields = ['id', 'credit', 'surrogate']


class PostImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, post_image):
        if post_image.image:
            return post_image.image.url
        return None

    class Meta:
        model = PostImage
        fields = ['height', 'width', 'image']


class PlaybackSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybackId
        fields = ['playback_id', 'policy']


class PostVideoSerializer(serializers.ModelSerializer):
    playback_ids = PlaybackSerializer(many=True)

    class Meta:
        model = PostVideo
        fields = ['asset_id', 'playback_ids']


class ReactObjectRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        if isinstance(value, Post):
            serializer = PostSerializer(value)
        else:
            raise Exception('Unexpected type of tagged object')
        return serializer.data


class ReactSerializer(serializers.ModelSerializer):
    class Meta:
        model = React
        fields = ['type', 'user']


class PostSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    linked_project = ProjectSerializer()
    images = PostImageSerializer(many=True)
    videos = PostVideoSerializer(many=True)
    reacted = serializers.SerializerMethodField()
    reacts = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, post):
        return post.surrogate

    def get_reacted(self, post):
        try:
            user = self.context['request'].user
            if user.reacts.filter(object_id=post.id, user=user).exists():
                return True
            return False
        except KeyError:
            return None

    def get_reacts(self, post):
        return post.reacts.count()

    def get_comment_count(self, post):
        return post.comments.count()

    class Meta:
        model = Post
        fields = ['status', 'text', 'coach', 'images', 'videos', 'tier', 'tiers',
                  'chained_posts', 'id', 'linked_project', 'reacted', 'reacts', 'comment_count']

    def get_fields(self):
        fields = super(PostSerializer, self).get_fields()
        fields['chained_posts'] = PostSerializer(many=True)
        return fields


class PostWithoutProjectSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    images = PostImageSerializer(many=True)
    videos = PostVideoSerializer(many=True)
    reacted = serializers.SerializerMethodField()
    reacts = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, post):
        return post.surrogate

    def get_reacted(self, post):
        try:
            user = self.context['request'].user
            if user.reacts.filter(object_id=post.id, user=user).exists():
                return True
            return False
        except KeyError:
            return None

    def get_reacts(self, post):
        return post.reacts.count()

    class Meta:
        model = Post
        fields = ['status', 'text', 'coach', 'images', 'videos', 'tier', 'tiers',
                  'chained_posts', 'id', 'reacted', 'reacts']

    def get_fields(self):
        fields = super(PostWithoutProjectSerializer, self).get_fields()
        fields['chained_posts'] = PostWithoutProjectSerializer(many=True)
        return fields


class PostNoChainSerializer(serializers.ModelSerializer):
    linked_project = ProjectSerializer()
    images = PostImageSerializer(many=True)
    videos = PostVideoSerializer(many=True)
    id = serializers.SerializerMethodField()

    def get_id(self, post):
        return post.surrogate

    class Meta:
        model = Post
        fields = ['status', 'text', 'images', 'videos', 'id', 'linked_project']


class PostCreateSerializer(serializers.ModelSerializer):
    coach = CoachSerializer(required=False)
    images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False)
    # tier = serializers.IntegerField(required=True)
    linked_project = serializers.UUIDField(required=False)
    has_videos = serializers.BooleanField(required=False)
    id = serializers.SerializerMethodField(required=False)

    def get_id(self, post):
        return post.surrogate

    def get_fields(self):
        fields = super(PostCreateSerializer, self).get_fields()
        fields['chained_posts'] = PostSerializer(many=True, required=False)
        return fields

    # FIXME
    # This should also return the whole linked_project as a ProjectSerializer instead of just the name
    def create(self, validated_data):
        coach = self.context['request'].user.coach

        if not validated_data.get('tier'):
            raise serializers.ValidationError({'error': 'A tier is required'})
        
        if not validated_data.get('text') and not validated_data.get('images') and not validated_data.get('has_videos'):
            raise serializers.ValidationError({'error': 'Post contains no data'})
        
        try:
            tier = validated_data.get('tier')

            # check if this tier belongs to the current user
            if tier.coach.pk != coach.pk:
                raise serializers.ValidationError({'error': 'Invalid tier'})
        except Exception as e:
            raise serializers.ValidationError({'error': 'Invalid tier'})

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []

        # try:
        #     tiers = validated_data.pop('tiers')
        # except KeyError:
        #     tiers = []

        try:
            linked_project_surrogate = validated_data.pop('linked_project')
        except KeyError:
            linked_project_surrogate = None

        linked_project = None
        if linked_project_surrogate:
            linked_project = Project.objects.filter(
                surrogate=linked_project_surrogate).first()

        try:
            has_videos = validated_data.pop('has_videos')
            status = Post.PROCESSING if has_videos else Post.DONE
        except KeyError:
            status = Post.DONE

        post = Post.objects.create(coach=coach,
                                   status=status, linked_project=linked_project, **validated_data)

        for image in images:
            PostImage.objects.create(post=post, coach=coach, image=image)
        # post.tiers.set(tiers)

        return post

    class Meta:
        model = Post
        fields = ['tier', 'text', 'images', 'videos', 'id',
                  'linked_project', 'chained_posts', 'coach', 'has_videos']
        read_only_fields = ['id', 'chained_posts', 'coach',
                            'videos', 'reacted', 'reacts', 'status']


class ChainedPostsSerializer(serializers.Serializer):
    posts = PostNoChainSerializer(many=True)

    def create(self, validated_data):
        coach = self.context['request'].user.coach
        results = {
            'posts': []
        }
        main_post = Post.objects.none()
        posts = validated_data.pop('posts')
        for i, post in enumerate(posts):

            # check if images exist then pop it from validation
            images = []
            try:
                images = post.pop('images')
            except KeyError:
                pass

            new_post = Post.objects.create(coach=coach, **post)

            # assign first post
            if i == 0:
                main_post = new_post
            # then chain the rest to the main post
            else:
                main_post.chained_posts.add(new_post)

            # set previously popped images
            new_post.images.set(images)

            results['posts'].append(new_post)
        return results

    def update(self, instance, validated_data):
        pass


class ChainPostsSerializer(serializers.Serializer):
    post_ids = serializers.JSONField()

    def create(self, validated_data):
        ids = validated_data['post_ids']  # .split(",")

        # convert all string ids to integers
        # ids = list(map(lambda item: int(item), ids))

        # get initial post to chain the rest
        main_post = Post.objects.get(surrogate=ids[0])

        # for each id chain it to the main_post
        for _id in ids:

            # ignore the first id
            if _id != ids[0]:
                post = Post.objects.get(surrogate=_id)
                main_post.chained_posts.add(post)

        return {"post_ids": ids}

    def update(self, instance, validated_data):
        pass


class CoachNewPosts(serializers.Serializer):
    coach = serializers.SerializerMethodField()
    new_posts = serializers.SerializerMethodField()

    def get_coach(self, coach):
        return CoachSerializer(coach, context={'request': self.context['request']}).data

    def get_new_posts(self, coach):
        return PostSerializer(coach.posts.exclude(parent_post__isnull=False),
                              context={'request': self.context['request']}, many=True).data

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    class Meta:
        fields = ['coach', 'new_posts']
        read_only_fields = fields


class NewPostsSerializer(serializers.Serializer):
    posts_per_coach = serializers.SerializerMethodField()

    def get_posts_per_coach(self, coach):
        return CoachNewPosts(coach).data

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    class Meta:
        fields = ['posts_per_coach']
        read_only_fields = fields


class CommentImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, comment_image):
        if comment_image.image:
            return comment_image.image.url
        return None

    class Meta:
        model = CommentImage
        fields = ['height', 'width', 'image']


class CommentSerializer(serializers.ModelSerializer):
    user = SubscriberSerializer()
    images = CommentImageSerializer(many=True)
    id = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    reacted = serializers.SerializerMethodField()
    reacts = serializers.SerializerMethodField()

    def get_id(self, comment):
        return comment.surrogate

    def get_reply_count(self, comment):
        return Comment.objects.filter(parent=comment.id).count()

    def get_reacted(self, comment):
        try:
            user = self.context['request'].user
            if user.reacts.filter(object_id=comment.id, user=user).exists():
                return True
            return False
        except KeyError:
            return None

    def get_reacts(self, comment):
        return comment.reacts.count()

    class Meta:
        model = Comment
        fields = ['id', 'text', 'images', 'user',
                  'level', 'parent', 'reply_count', 'reacted', 'reacts']


class CreateCommentSerializer(serializers.ModelSerializer):
    user = SubscriberSerializer(required=False)
    images = CommentImageSerializer(many=True, required=False)
    id = serializers.SerializerMethodField(required=False)
    parent = serializers.UUIDField(required=False)
    post = serializers.UUIDField(required=True)

    def get_id(self, comment):
        return comment.surrogate

    def get_parent(self, comment):
        return comment.id

    def create(self, validated_data):
        user = self.context['request'].user
        post = Post.objects.filter(surrogate=validated_data.pop('post')).first()

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []

        # check if this comment is a reply to another comment
        try:
            parent_id = validated_data.pop('parent')
            parent = Comment.objects.get(surrogate=parent_id)
        except KeyError:
            parent = None

        # if this comment is a reply to another comment get the parent posts author
        reply_to = parent.user if parent else None

        comment = Comment.objects.create(
            user=user.subscriber, parent=parent, post=post, reply_to=reply_to, **validated_data)
        comment.images.set(images)

        return comment

    class Meta:
        model = Comment
        fields = ['text', 'images', 'user', 'post', 'parent', 'id', 'level']
        read_only_fields = ['user', 'id', 'level']


class MyProjectsSerializer(serializers.ModelSerializer):
    prerequisites = PrerequisiteSerializer(many=True)
    difficulty = serializers.SerializerMethodField()
    milestones = serializers.SerializerMethodField()
    my_team = serializers.SerializerMethodField()
    coach_data = serializers.SerializerMethodField()
    coach = serializers.SerializerMethodField()
    linked_posts_count = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, project):
        return project.surrogate

    def get_my_team(self, project):
        user = self.context['request'].user
        if user:
            team = user.subscriber.teams.filter(project=project).first()
            return MyTeamsSerializer(team).data
        return None

    def get_milestones(self, project):
        user = self.context['request'].user
        team = user.subscriber.teams.filter(project=project).first()
        _milestones = []

        for milestone in project.milestones.all():
            completed = False
            reports = milestone.reports.filter(team=team)
            # if team in milestone.completed_teams.all():
            #     completed = True
            status = None
            if reports.filter(status=MilestoneCompletionReport.ACCEPTED).exists():
                status = 'accepted'
                completed = True
            elif reports.filter(status=MilestoneCompletionReport.REJECTED).exists():
                status = 'rejected'
            elif reports.filter(status=MilestoneCompletionReport.PENDING).exists():
                status = 'pending'

            _milestones.append({'description': milestone.description, 'completed': completed,
                                'status': status, 'id': milestone.id,
                                'reports': MilestoneCompletionReportSerializer(reports, many=True).data})
        return _milestones

    def get_coach_data(self, project):
        number_of_projects_joined = None
        my_tier = None

        try:
            user = self.context['request'].user
            if user.is_authenticated:
                if user.subscriber.subscriptions.filter(tier__coach=project.coach).exists():
                    subscription = user.subscriber.subscriptions.filter(
                        tier__coach=project.coach).first()
                    my_tier = subscription.tier
                    number_of_projects_joined = Team.objects.filter(
                        project__coach=project.coach, members__in=[user.subscriber]).count()
        except KeyError:
            number_of_projects_joined = None

        return {'number_of_projects_joined': number_of_projects_joined, "id": project.coach.surrogate, "my_tier": TierSerializer(my_tier).data}

    def get_coach(self, project):
        avatar = None
        if project.coach.avatar:
            avatar = project.coach.avatar.image.url
        return {'name': project.coach.name, 'avatar': avatar}

    def get_difficulty(self, obj):
        return obj.get_difficulty_display()

    def get_linked_posts_count(self, project):
        return project.posts.count()

    class Meta:
        model = Project
        fields = ['name', 'credit', 'description', 'difficulty', 'team_size', 'coach_data', 'coach',
                  'my_team', 'prerequisites', 'milestones', 'linked_posts_count', 'id']
        read_only_fields = ['id', 'credit', 'my_team', 'linked_posts', 'coach_data', 'coach']


class MyTeamsSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True)
    project = serializers.StringRelatedField()
    team_tier = serializers.SerializerMethodField()

    # this returns an overall "tier" to the team
    # for example if a team has a user with Tier 2 then the whole team
    # is classified as Tier 2
    def get_team_tier(self, team):
        tiers = []
        for member in team.members.all():
            subscription = member.subscriptions.filter(tier__coach=team.project.coach)
            if subscription.exists():
                subscription = subscription.first()
                tier = subscription.tier
                tiers.append(tier)
        # if any user is subscriber to Tier 2 the whole team is Tier 2
        if any(tier.tier == Tier.TIER2 for tier in tiers):
            return 2
        # if any user is subscriber to Tier 1 and no one is in Tier 2 the whole team is Tier 1
        if any(tier.tier == Tier.TIER1 for tier in tiers):
            return 1
        return None

    class Meta:
        model = Team
        fields = ['name', 'avatar', 'project', 'members', 'team_tier']


class TeamSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True)
    project = serializers.StringRelatedField()
    milestones = serializers.SerializerMethodField()
    team_tier = serializers.SerializerMethodField()

    # this returns an overall "tier" to the team
    # for example if a team has a user with Tier 2 then the whole team
    # is classified as Tier 2
    def get_team_tier(self, team):
        tiers = []
        for member in team.members.all():
            subscription = member.subscriptions.filter(tier__coach=team.project.coach)
            if subscription.exists():
                subscription = subscription.first()
                tier = subscription.tier
                tiers.append(tier)
        # if any user is subscriber to Tier 2 the whole team is Tier 2
        if any(tier.tier == Tier.TIER2 for tier in tiers):
            return 2
        # if any user is subscriber to Tier 1 and no one is in Tier 2 the whole team is Tier 1
        if any(tier.tier == Tier.TIER1 for tier in tiers):
            return 1
        return None

    def get_milestones(self, team):
        user = self.context['request'].user
        project = self.context['project']
        #team = user.subscriber.teams.filter(project=project).first()
        _milestones = []

        for milestone in project.milestones.all():
            completed = False
            reports = milestone.reports.filter(team=team)
            # if team in milestone.completed_teams.all():
            #     completed = True
            status = None
            if reports.filter(status=MilestoneCompletionReport.ACCEPTED).exists():
                status = 'accepted'
                completed = True
            elif reports.filter(status=MilestoneCompletionReport.REJECTED).exists():
                status = 'rejected'
            elif reports.filter(status=MilestoneCompletionReport.PENDING).exists():
                status = 'pending'

            _milestones.append({'description': milestone.description, 'completed': completed,
                                'status': status, 'id': milestone.id, 'surrogate': milestone.surrogate,
                                'reports': MilestoneCompletionReportSerializer(reports, many=True).data})
        return _milestones

    class Meta:
        model = Team
        fields = ['surrogate','name', 'avatar', 'project', 'members', 'milestones', 'team_tier']


class MilestoneCompletionReportExtendedSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True, required=False)
    images = MilestoneCompletionImageSerializer(many=True, required=False)
    videos = MilestoneCompletionVideoSerializer(many=True, required=False)
    milestone = MilestoneSerializer()
    project = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    reports = serializers.SerializerMethodField()

    def get_project(self, milestone_completion_report):
        return MyProjectsSerializer(milestone_completion_report.milestone.project, context=self.context).data

    def get_team(self, milestone_completion_report):
        context = {
            **self.context,
            'project': milestone_completion_report.team.project,
        }
        return TeamSerializer(milestone_completion_report.team, context=context).data

    def get_reports(self, milestone_completion_report):
        reports = milestone_completion_report.milestone.reports.filter(team=milestone_completion_report.team)
        return MilestoneCompletionReportSerializer(reports, many=True).data

    class Meta:
        model = MilestoneCompletionReport
        fields = ['members', 'message', 'milestone', 'project', 'team', 'reports', 'coach_feedback', 'status',
                  'images', 'videos', 'surrogate']
        read_only_fields = fields


class ExpertiseAvatarSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, expertise_avatar):
        if expertise_avatar.image:
            return expertise_avatar.image.url
        return None

    class Meta:
        model = ExpertiseFieldAvatar
        fields = ['width', 'height', 'image']


class ExpertiseSerializer(serializers.ModelSerializer):
    avatar = ExpertiseAvatarSerializer()

    class Meta:
        model = ExpertiseField
        fields = ['name', 'avatar']


class BenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Benefit
        fields = ['id', 'description']


class TierSerializer(serializers.ModelSerializer):
    tier_full = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()
    benefits = BenefitSerializer(many=True)

    def get_tier_full(self, obj):
        return obj.get_tier_display()

    def get_post_count(self, tier):
        return tier.posts.count()

    class Meta:
        model = Tier
        fields = ['id', 'surrogate', 'tier', 'tier_full',
                  'label', 'subheading', 'credit', 'benefits', 'post_count']
        read_only_fields = ['id', 'surrogate', 'tier', 'tier_full', 'post_count']


class UpdateTierSerializer(serializers.ModelSerializer):
    tier_full = serializers.SerializerMethodField()
    benefits = serializers.ListField(
        child=serializers.JSONField(), write_only=True, required=False)

    def get_tier_full(self, obj):
        return obj.get_tier_display()

    def update(self, instance, validated_data):
        try:
            benefits = validated_data.pop('benefits')
        except KeyError:
            benefits = []

        for benefit in benefits:
            benefit = json.loads(benefit)
            description = benefit.get('description')
            benefit_id = benefit.get('id', None)
            if benefit_id:
                if Benefit.objects.filter(id=benefit_id).exists():
                    update_benefit = Benefit.objects.filter(
                        id=benefit_id).first()
                    update_benefit.description = description
                    update_benefit.save()
            else:
                if description:
                    Benefit.objects.create(tier=instance, description=description)

        try:
            credit = validated_data.pop('credit')
            if instance.credit != credit:
                if isinstance(credit, Decimal):
                    price = stripe.Price.create(
                        unit_amount=money_to_integer(credit),
                        currency='eur',
                        recurring={"interval": "month"},
                        product=instance.product_id,
                    )
                else:
                    price = stripe.Price.create(
                        unit_amount=money_to_integer(credit),
                        currency=credit.currency.code.lower(),
                        recurring={"interval": "month"},
                        product=instance.product_id,
                    )
                instance.price_id = price.id
        except KeyError:
            pass

        instance = super(UpdateTierSerializer, self).update(
            instance, validated_data)
        return instance

    def to_representation(self, instance):
        # Since we use serializers.ListField for the benefits field the serializer won't return the
        # benefits property of the instance. That's why we use the TierSerializer which is defined above
        # to return the whole representation of the updated Tier
        return TierSerializer(instance).data

    class Meta:
        model = Tier
        fields = ['id', 'tier', 'tier_full', 'label',
                  'subheading', 'credit', 'benefits']
        read_only_fields = ['id', 'tier', 'tier_full']


class ChatRoomSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    def get_id(self, chat_room):
        return chat_room.surrogate

    def get_project(self, chat_room):
        return chat_room.project.surrogate

    def get_members(self, chat_room):
        return SubscriberSerializer(chat_room.members.all(), many=True).data

    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'team_type', 'members', 'project']


class MessageImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageImage
        fields = ['image', 'height', 'width']


class MessageSerializer(serializers.ModelSerializer):
    user = SubscriberSerializer()
    images = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_images(self, message):
        return MessageImageSerializer(message.images.all(), many=True).data

    def get_id(self, message):
        return message.surrogate

    class Meta:
        model = Message
        fields = ['text', 'created', 'user', 'images', 'id']


class CreateMessageSerializer(serializers.ModelSerializer):
    # message = MessageSerializer(required=False)
    images = serializers.ListField(
        child=serializers.ImageField(), write_only=False, required=False)
    chat_room = serializers.UUIDField(required=False)

    def create(self, validated_data):
        user = self.context['request'].user.subscriber

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []

        try:
            chat_room_surrogate = validated_data.pop('chat_room')
        except KeyError:
            chat_room_surrogate = None

        if chat_room_surrogate:
            chat_room = ChatRoom.objects.filter(surrogate=chat_room_surrogate)

        message = Message.objects.create(
            user=user, chat_room=chat_room.first(), **validated_data)

        # images_sent will be the object sent to the channel group
        images_sent = []
        for image in images:
            message_image = MessageImage.objects.create(
                message=message, image=image)
            images_sent.append({'height': message_image.height,
                               'width': message_image.width, 'image': message_image.image.url})

        channel_layer = channels.layers.get_channel_layer()
        # after message is created send it back to the group chat
        # a better idea is maybe to add this on a post_save signal
        async_to_sync(channel_layer.group_send)(
            'chat_%s' % chat_room_surrogate,
            {
                'type': 'chat.message',
                'message': message.text,
                'message_id': str(message.surrogate),
                'images': json.dumps(images_sent),
                'user_id': str(message.user.surrogate),
                'user_name': message.user.name,
                'user_avatar': message.user.avatar.image.url if message.user.avatar else None,
                'room': str(message.chat_room.surrogate)
            }
        )

        return {
            "id": message.surrogate
        }

    class Meta:
        model = Message
        fields = ['created', 'updated', 'chat_room', 'user', 'text', 'images']
        read_only_fields = ['created', 'updated', 'user']


class AwardBaseSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    def get_id(self, award):
        return award.surrogate

    class Meta:
        model = AwardBase
        fields = ['id', 'icon', 'is_primary', 'description']


class AwardSerializer(serializers.ModelSerializer):
    award = AwardBaseSerializer()
    project = ProjectSerializer()
    subscriber = SubscriberSerializer()

    class Meta:
        model = Award
        fields = '__all__'


class QuestionSerializer(serializers.ModelSerializer):
    delivered_by = CoachSerializer()

    class Meta:
        model = Question
        fields = '__all__'


class QuestionInvitationSerializer(serializers.ModelSerializer):
    question = QuestionSerializer()
    coach = CoachSerializer()

    class Meta:
        model = QuestionInvitation
        fields = '__all__'


class CreateAwardSerializer(serializers.ModelSerializer):
    project = serializers.UUIDField(required=False)
    report = serializers.UUIDField(required=False)
    subscribers = serializers.ListField(
        child=serializers.UUIDField(), write_only=True)
    award = serializers.UUIDField()

    def create(self, validated_data):
        user = self.context['request'].user.subscriber

        # get necessary objects from report
        # also try to get the project object through the milestone
        try:
            report = MilestoneCompletionReport.objects.get(surrogate=validated_data['report'])
            project = report.milestone.project
            milestone = report.milestone
        except KeyError:
            milestone = None
            project = None

        # if milestone was not present in the request search for a project
        # a use case for this would be 'project-wide' awards
        if not project:
            try:
                project = Project.objects.get(surrogate=validated_data['project'])
            except KeyError:
                project = None

        award_base = AwardBase.objects.get(surrogate=validated_data['award'])

        for subscriber_id in validated_data['subscribers']:
            subscriber = Subscriber.objects.get(surrogate=subscriber_id)
            award = Award.objects.create(project=project, milestone=milestone, subscriber=subscriber, award=award_base)
        
        return {
            'award': None
        }

    class Meta:
        model = Award
        fields = ['project', 'report', 'subscribers', 'award']


class GenericNotificationRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        request = self.context.get('request', None)
        context = {'request': request} if request else None

        if isinstance(value, Post):
            serializers = PostSerializer(value, context=context)
        if isinstance(value, Subscriber):
            serializers = SubscriberSerializer(value, context=context)
        if isinstance(value, Coach):
            serializers = CoachSerializer(value, context=context)
        if isinstance(value, ChatRoom):
            serializers = ChatRoomSerializer(value, context=context)
        if isinstance(value, MilestoneCompletionReport):
            serializers = MilestoneCompletionReportExtendedSerializer(value, context=context)
        if isinstance(value, Milestone):
            serializers = MilestoneSerializer(value, context=context)
        if isinstance(value, User):
            serializers = SubscriberSerializer(value.subscriber, context=context)
        if isinstance(value, Project):
            serializers = ProjectSerializer(value, context=context)
        try:
            return serializers.data
        except Exception as e:
            print(e)


class NotificationSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    actor = GenericNotificationRelatedField(read_only=True)
    recipient = UserSerializer(User, read_only=True)
    unread = serializers.BooleanField(read_only=True)
    target = GenericNotificationRelatedField(read_only=True)
    action_object = GenericNotificationRelatedField(read_only=True)
    verb = serializers.CharField(read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)
