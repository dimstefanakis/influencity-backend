from rest_framework import serializers
from accounts.models import User
from instructor.models import Coach, CoachApplication
from posts.models import Post, PostImage, PostVideo, PlaybackId
from projects.models import Project, Prerequisite, Milestone, Team, MilestoneCompletionReport, MilestoneCompletionImage
from comments.models import CommentImage, Comment
from subscribers.models import Subscriber, SubscriberAvatar
from expertisefields.models import ExpertiseField, ExpertiseFieldAvatar
from tiers.models import Tier, Benefit
from reacts.models import React
from chat.models import ChatRoom, Message
from babel.numbers import get_currency_precision
import stripe
import json
import os

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
def money_to_integer(money):
    return int(
        money.amount * (
            10 ** get_currency_precision(money.currency.code)
        )
    )

class CoachSerializer(serializers.ModelSerializer):
    expertise_field = serializers.StringRelatedField()
    avatar = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    tier = serializers.SerializerMethodField()
    tiers = serializers.SerializerMethodField()

    @staticmethod
    def get_projects(coach):
        return ProjectSerializer(coach.created_projects.all(), many=True).data

    @staticmethod
    def get_avatar(coach):
        if coach.avatar:
            return coach.avatar.image.url
        return None

    def get_tier(self, coach):
        user = self.context['request'].user
        if user.is_authenticated:
            if user.subscriptions.filter(coach=coach).exists():
                return user.subscriptions.filter(coach=coach).first().get_tier_display()

    def get_tiers(self, coach):
        return TierSerializer(coach.tiers.all(), many=True).data

    class Meta:
        model = Coach
        fields = ['name', 'avatar', 'bio', 'expertise_field', 'projects', 
                'tier', 'tiers', 'surrogate', 'charges_enabled']


class CoachApplicationSerializer(serializers.ModelSerializer):
    subscriber = serializers.StringRelatedField()

    def create(self, validated_data):
        user =  self.context['request'].user
        application = CoachApplication.objects.create(subscriber=user.subscriber, **validated_data)
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
        fields = ['name', 'avatar', 'id']
        read_only_fields = ['id']


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
            new_avatar = SubscriberAvatar.objects.create(subscriber=instance, image=avatar)
            #instance.avatar.image = avatar
        except KeyError:
            pass

        instance = super(SubscriberUpdateSerializer, self).update(instance, validated_data)
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
        fields = ['username', 'email', 'is_coach', 'is_subscriber', 'coach', 'subscriber']


class UserMeSerializer(serializers.ModelSerializer):
    coach = CoachSerializer()
    subscriber = SubscriberSerializer()
    subscriber_data = serializers.SerializerMethodField()

    def get_subscriber_data(self, user):
        if not user.coach:
            return None
        sub_count = user.coach.subscribers.count()
        free_sub_count = user.coach.subscribers.filter(subscriptions__tier=Tier.FREE).count()
        tier1_sub_count = user.coach.subscribers.filter(subscriptions__tier=Tier.TIER1).count()
        tier2_sub_count = user.coach.subscribers.filter(subscriptions__tier=Tier.TIER2).count()
        return {'subscribers_count': sub_count, 'free_subscribers_count': free_sub_count,
                'tier1_subscribers_count': tier1_sub_count, 'tier2_subscribers_count': tier2_sub_count}

    class Meta:
        model = User
        fields = ['username', 'email', 'is_coach', 'is_subscriber', 'coach', 'subscriber', 'subscriber_data']


class UserMeNoCoachSerializer(serializers.ModelSerializer):
    subscriber = SubscriberSerializer()

    class Meta:
        model = User
        fields = ['username', 'email', 'is_coach', 'is_subscriber', 'subscriber']

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


class MilestoneSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    def get_id(self, milestone):
        return milestone.surrogate

    class Meta:
        model = Milestone
        fields = ['description', 'id']
        read_only_fields = ['id']


class CreateMilestoneCompletionReportSerializer(serializers.ModelSerializer):
    members = serializers.ListField(child=serializers.UUIDField(), write_only=True)
    images = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False)

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

        milestone_report = MilestoneCompletionReport.objects.create(milestone_id=milestone_id, **validated_data)

        for image in images:
            MilestoneCompletionImage.objects.create(milestone_completion_report=milestone_report, image=image)

        for member in members:
            _member = Subscriber.objects.filter(surrogate=member)
            milestone_report.members.set(_member)
        return milestone_report

    class Meta:
        model = MilestoneCompletionReport
        fields = ['members', 'message', 'milestone', 'images']
        read_only_fields = ['milestone']


class MilestoneCompletionReportSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True, required=False)

    class Meta:
        model = MilestoneCompletionReport
        fields = ['members', 'message', 'milestone', 'images']
        read_only_fields = fields


class ProjectSerializer(serializers.ModelSerializer):
    prerequisites = PrerequisiteSerializer(many=True)
    milestones = MilestoneSerializer(many=True)
    difficulty = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, project):
        return project.surrogate

    def get_difficulty(self, project):
        return project.get_difficulty_display()

    class Meta:
        model = Project
        fields = ['name', 'description', 'difficulty', 'team_size', 'prerequisites', 'milestones', 'id']


class CreateOrUpdateProjectSerializer(serializers.ModelSerializer):
    # the below 2 contain a list of descriptions for both prerequisites and milestones
    prerequisites = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    milestones = serializers.ListField(child=serializers.JSONField(), write_only=True, required=False)
    attached_posts = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)

    def create(self, validated_data):
        coach = self.context['request'].user.coach

        try:
            prerequisites = validated_data.pop('prerequisites')
        except KeyError:
            prerequisites = []

        try:
            milestones = validated_data.pop('milestones')
        except KeyError:
            milestones = []

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
            Prerequisite.objects.create(description=prerequisite, project=project)

        for milestone in milestones:
            milestone = json.loads(milestone)
            Milestone.objects.create(description=milestone['description'], project=project)
        
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
            Prerequisite.objects.create(description=prerequisite, project=instance)

        # milestones need to be iterated and updated separately since they have
        # multiple relations attached to them
        try:
            milestones = validated_data.pop('milestones')
        except KeyError:
            milestones = []

        for milestone in milestones:
            milestone = json.loads(milestone)
            #try:
            milestone_instance = Milestone.objects.filter(surrogate=milestone['id'])
            if milestone_instance.exists():
                milestone_instance = milestone_instance.first()
                milestone_instance.description = milestone['description']
                milestone_instance.save()
            else:
                Milestone.objects.create(description=milestone['description'], project=instance)
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
            post.linked_project = project
            post.save()
        instance = super(CreateOrUpdateProjectSerializer, self).update(instance, validated_data)
        return instance

    class Meta:
        model = Project
        fields = ['name', 'description', 'difficulty', 'team_size', 
                'prerequisites', 'milestones', 'attached_posts', 'id', 'surrogate']
        read_only_fields = ['id', 'surrogate']


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
    # reacts = ReactSerializer()
    reacts = serializers.SerializerMethodField()
    id = serializers.SerializerMethodField()

    def get_id(self, post):
        return post.surrogate

    def get_reacted(self, post):
        user = self.context['request'].user
        if user.reacts.filter(object_id=post.id, user=user).exists():
            return True
        return False

    def get_reacts(self, post):
        return post.reacts.count()

    class Meta:
        model = Post
        fields = ['status','text', 'coach', 'images', 'videos', 'tiers', 
        'chained_posts', 'id', 'linked_project', 'reacted', 'reacts']

    def get_fields(self):
        fields = super(PostSerializer, self).get_fields()
        fields['chained_posts'] = PostSerializer(many=True)
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
        fields = ['status','text', 'images', 'videos', 'id', 'linked_project']


class PostCreateSerializer(serializers.ModelSerializer):
    coach = CoachSerializer(required=False)
    images = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False)
    linked_project = serializers.UUIDField(required=False)
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

        try:
            images = validated_data.pop('images')
        except KeyError:
            images = []

        try:
            tiers = validated_data.pop('tiers')
        except KeyError:
            tiers = []

        try:
            linked_project_surrogate = validated_data.pop('linked_project')
        except KeyError:
            linked_project_surrogate = None

        linked_project = None
        if linked_project_surrogate:
            linked_project = Project.objects.filter(surrogate=linked_project_surrogate).first()

        post = Post.objects.create(coach=coach, linked_project=linked_project, **validated_data)
        
        for image in images:
            PostImage.objects.create(post=post, coach=coach, image=image)
        post.tiers.set(tiers)

        return post

    class Meta:
        model = Post
        fields = ['text', 'images', 'videos', 'tiers', 'id', 'linked_project', 'chained_posts', 'coach']
        read_only_fields = ['id', 'chained_posts', 'coach', 'videos', 'reacted', 'reacts', 'status']


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

    def get_id(self, comment):
        return comment.surrogate

    def get_reply_count(self, comment):
        return Comment.objects.filter(parent=comment.id).count()

    class Meta:
        model = Comment
        fields = ['id', 'text', 'images', 'user', 'level', 'parent', 'reply_count']


class CreateCommentSerializer(serializers.ModelSerializer):
    user = SubscriberSerializer(required=False)
    images = CommentImageSerializer(many=True, required=False)
    id = serializers.SerializerMethodField(required=False)
    parent = serializers.UUIDField(required=False)

    def get_id(self, comment):
        return comment.surrogate

    def get_parent(self, comment):
        return comment.id

    def create(self, validated_data):
        user = self.context['request'].user

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

        comment = Comment.objects.create(user=user.subscriber, parent=parent, reply_to=reply_to, **validated_data)
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
            reports = milestone.reports.all()
            if team in milestone.completed_teams.all():
                completed = True
            status = None
            if reports.filter(status=MilestoneCompletionReport.ACCEPTED).exists():
                status = 'accepted'
            elif reports.filter(status=MilestoneCompletionReport.REJECTED).exists():
                status = 'rejected'
            elif reports.filter(status=MilestoneCompletionReport.PENDING).exists():
                status = 'pending'

            _milestones.append({'description': milestone.description, 'completed': completed,
                                'status': status, 'id': milestone.id,
                                'reports': MilestoneCompletionReportSerializer(reports, many=True).data})
        return _milestones

    def get_difficulty(self, obj):
        return obj.get_difficulty_display()

    class Meta:
        model = Project
        fields = ['name', 'description', 'difficulty', 'team_size', 'my_team', 'prerequisites', 'milestones', 'id']
        read_only_fields = ['id', 'my_team']


class MyTeamsSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True)
    project = serializers.StringRelatedField()

    class Meta:
        model = Team
        fields = ['name', 'avatar', 'project', 'members']


class TeamSerializer(serializers.ModelSerializer):
    members = SubscriberSerializer(many=True)
    project = serializers.StringRelatedField()
    milestones = serializers.SerializerMethodField()

    def get_milestones(self, team):
        user = self.context['request'].user
        project = self.context['project']
        #team = user.subscriber.teams.filter(project=project).first()
        _milestones = []

        for milestone in project.milestones.all():
            completed = False
            reports = milestone.reports.all()
            if team in milestone.completed_teams.all():
                completed = True
            status = None
            if reports.filter(status=MilestoneCompletionReport.ACCEPTED).exists():
                status = 'accepted'
            elif reports.filter(status=MilestoneCompletionReport.REJECTED).exists():
                status = 'rejected'
            elif reports.filter(status=MilestoneCompletionReport.PENDING).exists():
                status = 'pending'

            _milestones.append({'description': milestone.description, 'completed': completed,
                                'status': status, 'id': milestone.id,
                                'reports': MilestoneCompletionReportSerializer(reports, many=True).data})
        return _milestones

    class Meta:
        model = Team
        fields = ['name', 'avatar', 'project', 'members', 'milestones']


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
    benefits = BenefitSerializer(many=True)

    def get_tier_full(self, obj):
        return obj.get_tier_display()

    class Meta:
        model = Tier
        fields = ['id', 'surrogate', 'tier', 'tier_full', 'label', 'subheading', 'credit', 'benefits']
        read_only_fields = ['id', 'surrogate', 'tier', 'tier_full']


class UpdateTierSerializer(serializers.ModelSerializer):
    tier_full = serializers.SerializerMethodField()
    benefits = serializers.ListField(child=serializers.JSONField(), write_only=True, required=False)

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
                    update_benefit = Benefit.objects.filter(id=benefit_id).first()
                    update_benefit.description = description
                    update_benefit.save()
            else:
                Benefit.objects.create(tier=instance, description=description)

        try:
            credit = validated_data.pop('credit')
            if instance.credit != credit:
                price = stripe.Price.create(
                    unit_amount=money_to_integer(credit),
                    currency=credit.currency.code.lower(),
                    recurring={"interval": "month"},
                    product=instance.product_id,
                )
                instance.price_id = price.id
        except KeyError:
            pass

        instance = super(UpdateTierSerializer, self).update(instance, validated_data)
        return instance

    def to_representation(self, instance):
        # Since we use serializers.ListField for the benefits field the serializer won't return the
        # benefits property of the instance. That's why we use the TierSerializer which is defined above
        # to return the whole representation of the updated Tier
        return TierSerializer(instance).data

    class Meta:
        model = Tier
        fields = ['id', 'tier', 'tier_full', 'label', 'subheading', 'credit', 'benefits']
        read_only_fields = ['id', 'tier', 'tier_full']


class ChatRoomSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()

    def get_id(self, chat_room):
        return chat_room.surrogate

    def get_project(self, chat_room):
        return chat_room.project.surrogate

    class Meta:
        model = ChatRoom
        fields = ['id', 'name', 'type', 'members', 'project']


class MessageSerializer(serializers.ModelSerializer):
    user = SubscriberSerializer()
    id = serializers.SerializerMethodField()

    def get_id(self, message):
        return message.surrogate

    class Meta:
        model = Message
        fields = ['text', 'created', 'user', 'id']
